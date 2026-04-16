class CentralBank:
    """
    A class to represent a central bank and simulate its monetary policy decisions.

    Attributes
    ----------
    policy : str
        The bank's policy stance, either 'active' or 'passive'.
    interest_rate : float
        The current nominal interest rate set by the bank.
    target : float
        The central bank's target inflation rate.
    """

    def __init__(self, policy='passive', interest_rate=0.02, target=0.02): 
        """
        Initializes the CentralBank with a policy stance, initial rate, and target.
        """     
        self.policy = policy
        self.interest_rate = interest_rate
        self.target = target                                                   


    def react_to_inflation(self, current_inflation):     
        """
        Adjusts the interest rate based on the current inflation rate.
        
        An 'active' bank adjusts rates by 100 basis points (0.01), while a 
        'passive' bank adjusts by 25 basis points (0.0025).

        Parameters
        ----------
        current_inflation : float
            The current economic inflation rate to react to.
        """                       
        # 1. Determine the 'strength' of the reaction based on the policy attribute
        if self.policy == 'active':                             
            adjustment = 0.01   # 100 basis points              
        else:                                                   
            adjustment = 0.0025 # 25 basis points               

        # 2. Apply the adjustment logic
        if current_inflation > self.target:                     
            self.interest_rate += adjustment                    
            action = f"Hiked by {adjustment:.2%}"
        elif current_inflation < self.target:
            self.interest_rate -= adjustment                    
            action = f"Cut by {adjustment:.2%}"
        else:
            action = "Maintained"                               

        print(f"[{self.policy.upper()} BANK] Inflation: {current_inflation:.1%}, "              
              f"Target: {self.target:.1%} -> {action}. New Rate: {self.interest_rate:.2%}")     